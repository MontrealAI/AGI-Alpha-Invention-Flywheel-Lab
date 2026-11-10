# SPDX-License-Identifier: Apache-2.0
"""Structured-output contracts; synthetic senders only, no model inference."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime
from bridge.output_schema import SchemaError, prepare_schema, validate_output


def expression_schema(depth=4):
    definitions = {}
    for index in range(depth + 1):
        branches = [{"type": "number"}, {"type": "string"},
                    {"type": "object", "properties": {"field": {"type": "string", "minLength": 1}},
                     "required": ["field"], "additionalProperties": False}]
        if index:
            branches.append({"type": "object", "properties": {
                "op": {"type": "string", "enum": ["add", "mul"]},
                "args": {"type": "array", "items": {"$ref": "#/$defs/e" + str(index - 1)}, "minItems": 1, "maxItems": 8}},
                "required": ["op", "args"], "additionalProperties": False})
        definitions["e" + str(index)] = {"anyOf": branches}
    return {"type": "object", "$defs": definitions, "properties": {
        "summary": {"type": "string", "maxLength": 200},
        "outputs": {"type": "object", "additionalProperties": {"$ref": "#/$defs/e" + str(depth)}}},
        "required": ["summary", "outputs"], "additionalProperties": False}


def configuration(kind="openai", enabled=True, **extra):
    return {"local_only": True, "session_budget_usd": 100, "providers": {
        "fixture": {"kind": kind, "base_url": "http://127.0.0.1:1234/v1",
        "models": {"fixture-model": {"input_per_million": 1, "output_per_million": 1,
        "max_output_tokens": 256, "json_mode": True, "json_schema": enabled, "streaming": True}}}}, **extra}


def request(schema=None, **extra):
    return dict(provider="fixture", model="fixture-model", prompt="Return a generic expression object.",
                max_output_tokens=64, run_id="schema-run", json_schema=schema if schema is not None else expression_schema(), **extra)


def completion(text, kind="openai"):
    if kind == "ollama":
        return {"done": True, "done_reason": "stop", "message": {"content": text},
                "prompt_eval_count": 10, "eval_count": 20}
    return {"choices": [{"finish_reason": "stop", "message": {"content": text}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20}}


class SchemaTests(unittest.TestCase):
    def test_generic_local_references_preserve_valid_expressions_and_refuse_literal_wrappers(self):
        schema = prepare_schema(expression_schema(32))
        expr = {"field": "input_value"}
        for _ in range(32):
            expr = {"op": "add", "args": [expr, 1]}
        validate_output({"summary": "Generic expression", "outputs": {"arbitrary": expr}}, schema)
        for invalid in ({"literal": 2}, {"op": "run_shell", "args": [1]}, {"field": "x", "extra": True},
                        {"op": "add", "args": []}, {"op": "add", "args": [expr]}):
            with self.subTest(invalid=str(invalid)[:40]), self.assertRaises(SchemaError):
                validate_output({"summary": "Must fail", "outputs": {"arbitrary": invalid}}, schema)

    def test_schema_is_detached_and_numeric_boolean_equality_is_distinct(self):
        source = expression_schema()
        schema = prepare_schema(source)
        source["required"].clear()
        self.assertEqual(schema["required"], ["summary", "outputs"])
        validate_output(1.0, prepare_schema({"const": 1}))
        with self.assertRaises(SchemaError):
            validate_output(True, prepare_schema({"const": 1}))

    def test_unknown_keywords_unsafe_refs_and_unconstrained_objects_fail_closed(self):
        bad = [None, {}, True, {"type": "string", "pattern": "^.*$"},
               {"type": "number", "minimum": 1}, {"type": "object"},
               {"type": "object", "additionalProperties": True},
               {"type": "object", "additionalProperties": False, "minProperties": 1},
               {"$ref": "https://example.invalid/schema.json"},
               {"$defs": {"cycle": {"$ref": "#/$defs/cycle"}}, "$ref": "#/$defs/cycle"},
               {"$defs": {"a": {"type": "number"}}, "$ref": "#/$defs/a/other"},
               {"anyOf": [{"type": "string"}], "type": "number"},
               {"type": "number", "enum": [True]}, {"const": float("inf")}]
        for schema in bad:
            with self.subTest(schema=schema), self.assertRaises(SchemaError):
                prepare_schema(schema)

    def test_schema_resource_bounds_and_cycles_are_rejected(self):
        cycle = {}; cycle["self"] = cycle
        deep = {"type": "number"}
        for _ in range(50):
            deep = {"type": "array", "items": deep}
        cases = [cycle, deep, {"const": "x" * 262144},
                 {"type": "array", "items": {"type": "number"}, "maxItems": 4097},
                 {"type": "integer", "minimum": 9, "maximum": 2}]
        for schema in cases:
            with self.assertRaises(SchemaError):
                prepare_schema(schema)

    def test_exact_local_wire_contracts_and_capability_reporting(self):
        value = {"summary": "Constructed", "outputs": {"y": {"op": "mul", "args": [{"field": "x"}, 3]}}}
        for kind in ("openai", "ollama"):
            with self.subTest(kind=kind):
                calls = []
                def sender(url, headers, body, **kwargs):
                    calls.append(body)
                    return completion(json.dumps(value), kind)
                runtime = Runtime(configuration(kind), sender)
                result = runtime.generate(request())
                expected = prepare_schema(expression_schema())
                if kind == "openai":
                    self.assertEqual(calls[0]["response_format"], {"type": "json_schema", "json_schema": {
                        "name": "harness_output", "strict": True, "schema": expected}})
                else:
                    self.assertEqual(calls[0]["format"], expected)
                self.assertTrue(result["structured_output"]["validated"])
                self.assertTrue(runtime.status()["providers"][0]["model_capabilities"]["fixture-model"]["json_schema"])
                self.assertEqual(json.loads(result["text"]), value)

    def test_unconfigured_or_unsupported_schema_request_does_not_dispatch_or_reserve(self):
        calls = []
        for schema, enabled in ((expression_schema(), False), ({}, True), (None, True)):
            runtime = Runtime(configuration(enabled=enabled), lambda *a, **k: calls.append(a))
            payload = request(); payload["json_schema"] = schema
            with self.assertRaises(BridgeError):
                runtime.generate(payload)
            self.assertEqual(runtime._runs, {})
            self.assertEqual(runtime.budget.view()["reserved"], 0)
            self.assertEqual(runtime.budget.view()["committed"], 0)
        self.assertEqual(calls, [])
        for kind in ("responses", "anthropic", "gemini"):
            with self.assertRaises(BridgeError):
                Runtime(configuration(kind))
        remote = configuration(); remote["local_only"] = False
        remote["providers"]["fixture"]["base_url"] = "https://example.invalid/v1"
        with self.assertRaises(BridgeError):
            Runtime(remote)

    def test_invalid_completed_response_has_no_retry_and_preserves_consumed_accounting(self):
        for text in ('{"summary":"bad","outputs":{"x":{"literal":1}}}', '{"summary":',
                     '{"summary":"ok","summary":"duplicate","outputs":{}}'):
            calls = []
            def sender(*args, **kwargs):
                calls.append(True); return completion(text)
            runtime = Runtime(configuration(max_attempts=3), sender)
            with self.assertRaises(BridgeError) as failure:
                runtime.generate(request())
            self.assertEqual(failure.exception.code, "SCHEMA_RESPONSE")
            self.assertEqual(len(calls), 1)
            self.assertGreater(runtime.budget.view()["committed"], 0)
            self.assertEqual(runtime.budget.view()["reserved"], 0)

    def test_schema_transport_error_never_retries_or_falls_back(self):
        calls = []
        def sender(*args, **kwargs):
            calls.append(True)
            raise BridgeError("PROVIDER_HTTP", "Synthetic HTTP rejection", 400)
        runtime = Runtime(configuration(max_attempts=3), sender)
        with self.assertRaises(BridgeError):
            runtime.generate(request())
        self.assertEqual(calls, [True])

    def test_streamed_schema_output_is_withheld_until_validated(self):
        for valid in (False, True):
            text = json.dumps({"summary": "stream", "outputs": {"x": 2}}) if valid else '{"invalid":true}'
            events = []
            def streamer(*args, **kwargs):
                kwargs["on_text"](text[:5]); kwargs["on_text"](text[5:])
                self.assertEqual(events, [])
                return completion(text)
            runtime = Runtime(configuration(), streamer=streamer)
            if valid:
                runtime.generate(request(stream=True), events.append)
                self.assertEqual("".join(event["text"] for event in events), text)
            else:
                with self.assertRaises(BridgeError):
                    runtime.generate(request(stream=True), events.append)
                self.assertEqual(events, [])

    def test_schema_bytes_participate_in_declared_context_bound(self):
        config = configuration()
        config["providers"]["fixture"]["models"]["fixture-model"]["context_window"] = 4300
        runtime = Runtime(config, lambda *a, **k: self.fail("Context preflight must refuse dispatch"))
        with self.assertRaises(BridgeError) as failure:
            runtime.generate(request())
        self.assertEqual(failure.exception.code, "CONTEXT")
        self.assertEqual(runtime._runs, {})

    def test_stream_events_use_the_validated_final_text_when_fragments_differ(self):
        text = json.dumps({"summary": "accepted final text", "outputs": {"x": 2}})
        def streamer(*args, **kwargs):
            kwargs["on_text"]('{"invalid":"unaccepted intermediate text"}')
            return completion(text)
        events = []
        result = Runtime(configuration(), streamer=streamer).generate(request(stream=True), events.append)
        self.assertEqual("".join(event["text"] for event in events), result["text"])
        self.assertEqual(result["text"], text)

    def test_schema_routing_is_explicit_and_native_tools_cannot_bypass_it(self):
        config = configuration(stage_routes={"builder": {"provider": "fixture", "model": "fixture-model"}})
        config["providers"]["fixture"]["models"]["fixture-model"]["json_mode"] = False
        runtime = Runtime(config, lambda *a, **k: self.fail("No provider request expected"))
        self.assertEqual(runtime.route("builder", ["json_schema"]), config["stage_routes"]["builder"])
        with self.assertRaises(BridgeError):
            runtime.generate(request(tools=[{"name": "native_tool", "parameters": {"type": "object"}}]))
        self.assertEqual(runtime._runs, {})
        config["providers"]["fixture"]["models"]["fixture-model"]["json_schema"] = False
        with self.assertRaises(BridgeError):
            Runtime(config).route("builder", ["json_schema"])


if __name__ == "__main__":
    unittest.main()
