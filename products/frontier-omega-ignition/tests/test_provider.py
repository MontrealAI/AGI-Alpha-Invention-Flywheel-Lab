import hashlib
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
import time
import unittest

from ignition.provider import MAX_REPLY, HandoffRequired, LocalProvider, ManualProvider, ModelProvider, ProviderUnavailable


def completed(model="unit-model", answer='{"result":1}', **changes):
    response = {"model": model, "choices": [
        {"finish_reason": "stop", "message": {"content": answer}}],
        "usage": {"prompt_tokens": 21, "completion_tokens": 6}}
    return dict(response, **changes)


def frame(content=None, finish=None, model="unit-model", **extra_delta):
    delta = {} if content is None else {"content": content}
    return {"model": model, "choices": [{"index": 0, "delta": {**delta, **extra_delta}, "finish_reason": finish}]}


@contextmanager
def local_sse(events, *, delays=(), timeout=1, wall_timeout=None):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for index, event in enumerate(events):
                if index < len(delays):
                    time.sleep(delays[index])
                data = event if isinstance(event, str) else json.dumps(event)
                try:
                    self.wfile.write(("data: " + data + "\n\n").encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        try:
            yield LocalProvider("llama-cpp", "unit-model", server.server_port, timeout=timeout,
                                schema_output=True, streaming=True, wall_timeout=wall_timeout), requests
        finally:
            server.shutdown()
            thread.join()


class ProviderTests(unittest.TestCase):
    def test_default_has_no_effects_and_config_is_operator_owned(self):
        provider = ModelProvider.from_environment({})
        self.assertEqual(provider.identity()["mode"], "unavailable")
        with self.assertRaises(ProviderUnavailable):
            provider.propose("build", {"url": "http://invalid", "tools": ["shell"]})
        self.assertEqual(provider.receipts, [])
        for env in [{"IGNITION_MODEL_PROVIDER": "https://elsewhere"},
                    {"IGNITION_MODEL_PROVIDER": "llama-cpp", "IGNITION_MODEL_PORT": "80/other"},
                    {"IGNITION_MODEL_PROVIDER": "llama-cpp", "IGNITION_MODEL_ID": "m", "IGNITION_MODEL_STREAM": "yes"},
                    {"IGNITION_MODEL_PROVIDER": "ollama", "IGNITION_MODEL_ID": "m", "IGNITION_MODEL_STREAM": "1"},
                    {"IGNITION_MODEL_PROVIDER": "ollama", "IGNITION_MODEL_ID": "abc:cloud"}]:
            with self.assertRaises(ProviderUnavailable):
                ModelProvider.from_environment(env)

    def test_stream_progress_may_outlast_an_idle_interval_and_preserves_schema_identity(self):
        events = [frame('{"choice":'), frame('"abstain"}'), frame(finish="stop"),
                  {"model": "unit-model", "choices": [], "usage": {"prompt_tokens": 20, "completion_tokens": 10}},
                  "[DONE]"]
        with local_sse(events, delays=(0, .6, .6)) as (route, requests):
            self.assertEqual(route.propose("choose_hypothesis", {"candidates": []}), {"choice": "abstain"})
            self.assertEqual(len(requests), 1)
            path, headers, body = requests[0]
            self.assertEqual(path, "/v1/chat/completions")
            self.assertEqual(headers["Accept"], "text/event-stream")
            self.assertNotIn("Authorization", headers)
            self.assertNotIn("tools", body)
            self.assertIs(body["stream"], True)
            self.assertEqual(body["response_format"]["type"], "json_schema")
            receipt = route.receipts[-1]
            self.assertEqual(receipt["reported_model"], route.model)
            self.assertEqual(receipt["transport_mode"], "streaming-sse/1")
            self.assertEqual(receipt["stream_fragments"], 2)
            self.assertEqual(receipt["usage"], {"input_tokens": 20, "output_tokens": 10})
            self.assertGreater(receipt["wall_seconds"], route.timeout)

    def test_total_wall_budget_interrupts_an_active_loopback_stream(self):
        frames = [frame('{"choice":'), frame('"abstain"}'), frame(finish="stop"), "[DONE]"]
        with local_sse(frames, delays=(0, .65, .65), timeout=3, wall_timeout=1) as (provider, calls):
            with self.assertRaisesRegex(ProviderUnavailable, "PROVIDER_WALL_LIMIT"):
                provider.propose("choose_hypothesis", {"candidates": []})
            self.assertEqual(len(calls), 1)
            self.assertEqual(provider.identity()["wall_timeout_seconds"], 1)
            receipt = provider.receipts[-1]
            self.assertIsNone(receipt["response_sha256"])
            self.assertEqual(receipt["application_model_calls"], 1)
            self.assertLess(receipt["wall_seconds"], 1.5)

    def test_complete_loopback_stream_can_pass_under_the_wall_budget(self):
        frames = [frame('{"choice":"abstain"}'), frame(finish="stop"), "[DONE]"]
        with local_sse(frames, wall_timeout=1) as (provider, calls):
            self.assertEqual(provider.propose("choose_hypothesis", {"candidates": []}), {"choice": "abstain"})
            self.assertEqual(len(calls), 1)

    def test_stream_rejects_partial_wrong_identity_undeclared_tools_oversize_or_invalid_schema(self):
        answer, stop = frame('{"choice":"abstain"}'), frame(finish="stop")
        for label, events in {
            "no terminal": [answer, "[DONE]"],
            "no end marker": [answer, stop],
            "early end marker": [answer, "[DONE]", stop],
            "wrong earlier identity": [frame('{"choice":', model="other"), frame('"abstain"}'), stop, "[DONE]"],
            "missing model": [{k:v for k,v in answer.items() if k != "model"}, stop, "[DONE]"],
            "multiple choices": [dict(answer, choices=answer["choices"]*2), stop, "[DONE]"],
            "truncated": [answer, frame(finish="length"), "[DONE]"],
            "duplicate terminal": [answer, stop, stop, "[DONE]"],
            "unexpected content type": [frame(0), answer, stop, "[DONE]"],
            "late content": [answer, stop, frame(" "), "[DONE]"],
            "tool": [answer, frame(tool_calls=[{"index":0}]), stop, "[DONE]"],
            "legacy tool": [answer, frame(function_call={"name":"x"}), stop, "[DONE]"],
            "schema mismatch": [frame('{"choice":"unknown"}'), stop, "[DONE]"],
            "output bytes": [frame(" "*(MAX_REPLY+1)), stop, "[DONE]"],
            "reported tokens": [answer, stop, {"model":"unit-model","choices":[],
                                                "usage":{"prompt_tokens":20,"completion_tokens":4097}}, "[DONE]"],
        }.items():
            with self.subTest(label=label), local_sse(events) as (route, requests):
                with self.assertRaises(ProviderUnavailable):
                    route.propose("choose_hypothesis", {"candidates": []})
                self.assertEqual(len(requests), 1)
                self.assertEqual(route.receipts[-1]["status"], "failed")
                self.assertIsNone(route.receipts[-1]["response_sha256"])

    def test_stream_idle_before_completion_records_interruption_without_a_retry(self):
        with local_sse([frame("{}"), frame(finish="stop"), "[DONE]"], delays=(0, 1.25)) as (route, requests):
            with self.assertRaisesRegex(ProviderUnavailable, "PROVIDER_CONNECTION"):
                route.propose("build", {})
            self.assertEqual(len(requests), 1)
            self.assertEqual(route.receipts[-1]["stream_fragments"], 1)
            self.assertIsNone(route.receipts[-1]["response_sha256"])

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
