# SPDX-License-Identifier: Apache-2.0
"""Real qualifier observation classes must preserve ordinary execution admission."""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import BridgeError, Runtime
from bridge.services import AccessRuntime
from bridge.workflows import WorkflowService

DRIVERS = ("probe_local_workflows.py", "qualify_quote_workflow_006.py")


def observation_class(driver):
    """Load the actual nested class without starting a CLI server or inference."""
    path = ROOT / "scripts" / driver
    tree = ast.parse(path.read_text())
    classes = [node for node in ast.walk(tree)
               if isinstance(node, ast.ClassDef) and node.name == "ObservedRuntime"]
    if len(classes) != 1:
        raise AssertionError("Qualifier must contain one reviewed observation class")
    namespace = dict(Runtime=Runtime, hashlib=hashlib, json=json, time=time, observations=[])
    exec(compile(ast.Module(body=classes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["ObservedRuntime"], namespace["observations"]


def configuration():
    return {"local_only": True, "max_attempts": 1, "providers": {
        "local": {"kind": "openai", "base_url": "http://127.0.0.1:1234/v1", "models": {
            "fixture": {"input_per_million": 0, "output_per_million": 0,
                        "max_output_tokens": 64}}}}}


def request():
    return {"provider": "local", "model": "fixture", "run_id": "observed-guard",
            "prompt": "Public synthetic qualification fixture", "max_output_tokens": 32}


class ObservedRuntimeGuards(unittest.TestCase):
    def test_real_observers_are_wrapped_by_normal_workflow_admission(self):
        for driver in DRIVERS:
            with self.subTest(driver=driver), tempfile.TemporaryDirectory() as temporary:
                observed, _ = observation_class(driver)
                self.assertTrue(issubclass(observed, Runtime))
                runtime = observed(configuration(), sender=Mock(side_effect=AssertionError("Unexpected transport")))
                service = WorkflowService(runtime, temporary)
                try:
                    self.assertIsInstance(service.runtime, AccessRuntime)
                    self.assertIs(service.runtime.base, runtime)
                    # AccessRuntime discovers these named parameters, not arbitrary **kwargs.
                    parameters = inspect.signature(runtime.generate).parameters
                    self.assertIn("cancelled_before_dispatch", parameters)
                    self.assertIn("expected_provider", parameters)
                finally:
                    service.close()

    def test_admitted_call_forwards_both_guards_and_keeps_observation(self):
        original_generate = Runtime.generate
        for driver in DRIVERS:
            with self.subTest(driver=driver):
                observed, observations = observation_class(driver)
                sender = Mock(return_value={"choices": [{"message": {"content": "synthetic response"}}],
                                            "usage": {"prompt_tokens": 3, "completion_tokens": 2}})
                runtime = observed(configuration(), sender=sender)
                forwarded = []
                def checked_generate(target, data, **kwargs):
                    forwarded.append(kwargs)
                    return original_generate(target, data, **kwargs)
                with patch.object(Runtime, "generate", checked_generate):
                    result = AccessRuntime(runtime).generate(request())
                self.assertEqual(len(forwarded), 1)
                self.assertIs(forwarded[0]["expected_provider"], runtime.provider("local"))
                self.assertTrue(callable(forwarded[0]["cancelled_before_dispatch"]))
                self.assertEqual(sender.call_count, 1)
                self.assertEqual(result["text"], "synthetic response")
                self.assertEqual(len(observations), 1)
                self.assertEqual(observations[0]["response"], result)

    def test_cancelled_observation_never_dispatches_or_reserves(self):
        for driver in DRIVERS:
            with self.subTest(driver=driver):
                observed, observations = observation_class(driver)
                sender = Mock(side_effect=AssertionError("Cancelled request reached transport"))
                runtime = observed(configuration(), sender=sender)
                reserve = Mock(wraps=runtime.budget.reserve)
                with patch.object(runtime.budget, "reserve", reserve), self.assertRaises(BridgeError) as failure:
                    runtime.generate(request(), cancelled_before_dispatch=lambda: True,
                                     expected_provider=runtime.provider("local"))
                self.assertEqual(failure.exception.code, "CANCELLED")
                self.assertTrue(failure.exception.pre_dispatch)
                sender.assert_not_called()
                reserve.assert_not_called()
                self.assertEqual(observations[0]["error_code"], "CANCELLED")

    def test_stale_provider_observation_never_dispatches_or_reserves(self):
        for driver in DRIVERS:
            with self.subTest(driver=driver):
                observed, observations = observation_class(driver)
                sender = Mock(side_effect=AssertionError("Stale provider reached transport"))
                runtime = observed(configuration(), sender=sender)
                reserve = Mock(wraps=runtime.budget.reserve)
                with patch.object(runtime.budget, "reserve", reserve), self.assertRaises(BridgeError) as failure:
                    runtime.generate(request(), cancelled_before_dispatch=lambda: False,
                                     expected_provider=object())
                self.assertEqual(failure.exception.code, "PROVIDER_CHANGED")
                self.assertTrue(failure.exception.pre_dispatch)
                sender.assert_not_called()
                reserve.assert_not_called()
                self.assertEqual(observations[0]["error_code"], "PROVIDER_CHANGED")


if __name__ == "__main__":
    unittest.main()
