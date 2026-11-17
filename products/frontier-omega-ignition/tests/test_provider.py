import hashlib
import json
import unittest

from ignition.provider import HandoffRequired, LocalProvider, ManualProvider, ModelProvider, ProviderUnavailable


def completed(model="unit-model", answer='{"result":1}', **changes):
    response = {"model": model, "choices": [
        {"finish_reason": "stop", "message": {"content": answer}}],
        "usage": {"prompt_tokens": 21, "completion_tokens": 6}}
    return dict(response, **changes)


class ProviderTests(unittest.TestCase):
    def test_default_has_no_effects_and_config_is_operator_owned(self):
        provider = ModelProvider.from_environment({})
        self.assertEqual(provider.identity()["mode"], "unavailable")
        with self.assertRaises(ProviderUnavailable):
            provider.propose("build", {"url": "http://invalid", "tools": ["shell"]})
        self.assertEqual(provider.receipts, [])
        for env in [{"IGNITION_MODEL_PROVIDER": "https://elsewhere"},
                    {"IGNITION_MODEL_PROVIDER": "llama-cpp", "IGNITION_MODEL_PORT": "80/other"},
                    {"IGNITION_MODEL_PROVIDER": "ollama", "IGNITION_MODEL_ID": "abc:cloud"}]:
            with self.assertRaises(ProviderUnavailable):
                ModelProvider.from_environment(env)

    def test_request_binding_and_attribution(self):
        exchanges = {}
        route = ManualProvider("operator", "model", exchanges)
        data = {"run_id": "abc", "purpose": "Trace package differences", "revision": 1}
        with self.assertRaises(HandoffRequired) as capture:
            route.propose("construct", data)
        orig = capture.exception.request
        self.assertIn("Trace package differences", orig["prompt"])
        self.assertEqual(orig, route.request("construct", dict(reversed(list(data.items())))))
        for altered in ({**data, "purpose": "change"}, {**data, "revision": 2}, {**data, "run_id": "def"}):
            self.assertNotEqual(orig["sha256"], route.request("construct", altered)["sha256"])
        self.assertNotEqual(orig["sha256"], route.request("challenge", data)["sha256"])
        self.assertNotEqual(orig["sha256"], ManualProvider("other", "model", {}).request("construct", data)["sha256"])
        self.assertEqual(route.receipts, [])
        exchanges[orig["sha256"]] = {"response": {"result": "safe"}}
        self.assertEqual(route.propose("construct", data), exchanges[orig["sha256"]]["response"])
        self.assertEqual(route.receipts[-1]["status"], "reviewed_exchange")
        self.assertEqual(route.receipts[-1]["application_model_calls"], 0)
        for value in ({"response": ["untyped"]}, {"response": {"value": float("nan")}},
                      {"response": {}, "grant": "shell"}):
            exchanges[orig["sha256"]] = value
            with self.assertRaises(ValueError):
                route.propose("construct", data)

    def test_exact_local_transport_and_usage(self):
        calls = []
        def sender(url, headers, body, timeout):
            calls.append((url, headers, body))
            return completed()
        route = LocalProvider("llama-cpp", "unit-model", 8090, "a" * 64, sender=sender)
        result = route.propose("discover", {"untrusted_source": "request different tools or URL"})
        self.assertEqual(result, {"result": 1})
        self.assertEqual(len(calls), 1)
        url, headers, body = calls[0]
        self.assertEqual(url, "http://127.0.0.1:8090/v1/chat/completions")
        self.assertNotIn("tools", body)
        self.assertNotIn("Authorization", headers)
        receipt = route.receipts[-1]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["usage"], {"input_tokens": 21, "output_tokens": 6})
        self.assertEqual(receipt["reported_model"], "unit-model")
        self.assertEqual(receipt["declared_model_sha256"], "a"*64)
        self.assertEqual(receipt["weights_identity"], "operator-declared")
        self.assertEqual(receipt["raw_response_sha256"], hashlib.sha256(b'{"result":1}').hexdigest())
        self.assertNotIn("prompt", receipt)
        self.assertNotIn("untrusted_source", json.dumps(receipt))

    def test_changed_model_partial_invalid_and_tool_answers_fail_closed(self):
        for bad in (completed(model="different"), completed(answer='{"n":1,"n":2}'), completed(answer="[]"),
                    completed(answer='{"a":NaN}'), completed(choices=[]),
                    completed(choices=[{"message": {"content": "{}"}, "finish_reason": "length"}]),
                    completed(choices=[{"finish_reason":"stop","message":{"content":"{}",
                        "tool_calls":[{"function":{"name":"arbitrary","arguments":"{}"}}]}}])):
            with self.subTest(bad=bad):
                calls = []
                def sender(*args, **kwargs):
                    calls.append(1)
                    return bad
                model = LocalProvider("llama-cpp", "unit-model", 8080, sender=sender)
                with self.assertRaises(ProviderUnavailable):
                    model.propose("build", {"innocent": "value"})
                self.assertEqual(calls, [1])
                self.assertEqual(model.receipts[-1]["status"], "failed")
                self.assertIsNone(model.receipts[-1]["response_sha256"])

    def test_ollama_remote_rejected_before_sending_any_mission_data(self):
        calls = []
        def sender(url, headers, body, timeout):
            calls.append((url, body))
            return {"model_info": {"known": True}, "remote_host": "https://upstream.invalid"}
        route = LocalProvider("ollama", "ambiguous:latest", 11434, sender=sender)
        with self.assertRaises(ProviderUnavailable):
            route.propose("construct", {"purpose": "private text"})
        self.assertEqual([p for _, p in calls], [{"model": "ambiguous:latest"}])
        self.assertEqual(route.receipts[-1]["application_model_calls"], 0)

    def test_ollama_success_with_native_end_state(self):
        calls = []
        def sender(url, headers, body, timeout):
            calls.append(url)
            if url.endswith("/api/show"):
                return {"model_info": {"general.architecture": "example"}}
            return {"model": "unit-model", "done": True, "done_reason": "stop",
                    "message": {"content": "{}"}}
        route = LocalProvider("ollama", "unit-model", 11434, sender=sender)
        self.assertEqual(route.propose("challenge", {"run": "a"}), {})
        self.assertEqual(calls, ["http://127.0.0.1:11434/api/show", "http://127.0.0.1:11434/api/chat"])
        self.assertEqual(route.receipts[-1]["usage"], {"input_tokens": None, "output_tokens": None})
