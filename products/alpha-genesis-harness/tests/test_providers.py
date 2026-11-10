# SPDX-License-Identifier: Apache-2.0
"""No live cloud traffic: protocol, bounded stream, routing and actual loopback tests."""
import http.client
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime, Provider
from bridge.streaming import StreamAccumulator


def config(kind="responses", **extra):
    return {"local_only": True, "providers": {"local": {"kind": kind, "base_url": "http://127.0.0.1:1234/v1",
            "models": {"configured-model": {"input_per_million": 0, "output_per_million": 0,
            "streaming": True, "tool_calling": True, "json_mode": kind != "anthropic", "max_output_tokens": 256,
            "context_window": 32768}}}}, **extra}


def request(**extra):
    return dict(provider="local", model="configured-model", prompt="Construct a useful artifact.", max_output_tokens=64,
                run_id="provider-test", **extra)


def tool():
    return {"name": "write_artifact", "description": "Write an authorized artifact", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}}}


def final_response():
    return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "result"}]}],
            "usage": {"input_tokens": 10, "output_tokens": 6}, "model":"served-model-revision"}


class ProviderExtensionTests(unittest.TestCase):
    def test_responses_contract_and_accounting(self):
        calls=[]
        def sender(url,headers,body,**kw):
            calls.append((url,body));return final_response()
        r=Runtime(config(), sender)
        result=r.generate(request(json_mode=True))
        self.assertEqual(calls[0][0], "http://127.0.0.1:1234/v1/responses")
        self.assertFalse(calls[0][1]["store"])
        self.assertEqual(calls[0][1]["text"]["format"], {"type":"json_object"})
        self.assertEqual(result["usage_class"], "local_compute")
        self.assertEqual(result["text"], "result")
        self.assertEqual(result["reported_model"],"served-model-revision")

    def test_native_tool_calls_all_protocols(self):
        fixtures={
          "responses":{"status":"completed","output":[{"type":"function_call","call_id":"a","name":"write_artifact","arguments":'{"text":"x"}'}]},
          "openai":{"choices":[{"message":{"tool_calls":[{"id":"a","function":{"name":"write_artifact","arguments":'{"text":"x"}'}}]}}]},
          "anthropic":{"content":[{"type":"tool_use","id":"a","name":"write_artifact","input":{"text":"x"}}]},
          "gemini":{"candidates":[{"content":{"parts":[{"functionCall":{"name":"write_artifact","args":{"text":"x"}}}]}}]},
          "ollama":{"message":{"content":"","tool_calls":[{"function":{"name":"write_artifact","arguments":{"text":"x"}}}]}}
        }
        for kind,response in fixtures.items():
            with self.subTest(kind=kind):
                result=Runtime(config(kind),lambda *a,**kw:response).generate(request(tools=[tool()]))
                self.assertEqual(result["tool_calls"][0]["arguments"],{"text":"x"})
                self.assertEqual(result["text"],"")

    def test_undeclared_or_malformed_tool_never_authorized(self):
        response={"status":"completed","output":[{"type":"function_call","call_id":"a","name":"write_artifact","arguments":"{}"}]}
        r=Runtime(config(),lambda *a,**kw:response)
        with self.assertRaisesRegex(BridgeError,"outside"):r.generate(request())
        for bad in [[{"name":"shell", "parameters":{"type":"string"}}], [tool(),tool()]]:
            with self.assertRaises(BridgeError):Runtime(config()).generate(request(tools=bad))

    def test_local_only_rejects_remote_even_with_consent(self):
        c=config(allow_paid_requests=True)
        c["providers"]["local"]["base_url"]="https://api.example.com/v1"
        with self.assertRaisesRegex(BridgeError,"Local-only"):Runtime(c)
        self.assertEqual(Runtime(config()).status()["source_hosts"],[])

    def test_explicit_routes_and_capability_refusal(self):
        c=config(stage_routes={"builder":{"provider":"local","model":"configured-model"}})
        r=Runtime(c)
        self.assertEqual(r.route("builder",["tool_calling"])["provider"],"local")
        with self.assertRaises(BridgeError):r.route("critic")
        c["providers"]["local"]["models"]["configured-model"]["tool_calling"]=False
        r=Runtime(c,lambda *a,**kw:self.fail("No dispatch"))
        with self.assertRaises(BridgeError):r.generate(request(tools=[tool()]))

    def test_context_checks_tool_schema_and_prompt(self):
        c=config()
        c["providers"]["local"]["models"]["configured-model"].update(context_window=4200)
        r=Runtime(c,lambda *a,**kw:self.fail("No dispatch"))
        with self.assertRaisesRegex(BridgeError,"context"):r.generate(request(tools=[tool()]))

    def test_status_model_capabilities_are_configured(self):
        p=Runtime(config()).status()["providers"][0]
        self.assertEqual(p["category"],"local")
        self.assertFalse(p["remote"])
        self.assertTrue(p["model_capabilities"]["configured-model"]["streaming"])
        self.assertEqual(p["qualification"],"CONTRACT_TESTED_ONLY")

    def test_stream_secret_spanning_fragments_redacted(self):
        c=config();c["providers"]["local"]["key_env"]="HARNESS_FIXTURE_KEY"
        def streamer(*a,on_text,**kw):
            for part in ["prefix-", "known-", "fixture-", "secret", "-suffix"]:on_text(part)
            return final_response()
        with patch.dict(os.environ,{"HARNESS_FIXTURE_KEY":"known-fixture-secret"}):
            r=Runtime(c,streamer=streamer);events=[]
            r.generate(request(stream=True),events.append)
        value="".join(e["text"] for e in events)
        self.assertNotIn("known-fixture-secret",value)
        self.assertIn("[credential redacted]",value)


class StreamTests(unittest.TestCase):
    def test_terminal_required_for_every_protocol(self):
        for kind in ["responses","openai","anthropic","gemini","ollama"]:
            with self.subTest(kind=kind),self.assertRaises(BridgeError):StreamAccumulator(kind).finish()

    def test_five_protocol_text_streams(self):
        streams={
          "responses":[{"type":"response.output_text.delta","delta":"result"},{"type":"response.completed","response":final_response()}],
          "openai":[{"choices":[{"delta":{"content":"result"},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":6}}],
          "anthropic":[{"type":"message_start","message":{"usage":{"input_tokens":10}}},{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"result"}},{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":6}},{"type":"message_stop"}],
          "gemini":[{"candidates":[{"content":{"parts":[{"text":"result"}]},"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":10,"candidatesTokenCount":6}}],
          "ollama":[{"message":{"content":"result"},"done":True,"done_reason":"stop","prompt_eval_count":10,"eval_count":6}]
        }
        for kind,events in streams.items():
            with self.subTest(kind=kind):
                acc=StreamAccumulator(kind);acc.end_marker=True
                for event in events:acc.feed(event)
                text,usage=Runtime(config(kind)).providers["local"].parse(acc.finish())
                self.assertEqual(text,"result");self.assertEqual(usage,{"input_tokens":10,"output_tokens":6})

    def test_partial_tool_arguments_and_truncation(self):
        acc=StreamAccumulator("openai")
        acc.feed({"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call1","function":{"name":"write_artifact","arguments":'{"text":'}}]}}]})
        acc.feed({"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":'"hello"}'}}]},"finish_reason":"tool_calls"}]})
        acc.end_marker=True
        calls=Runtime(config("openai")).providers["local"].tool_calls(acc.finish())
        self.assertEqual(calls[0]["arguments"],{"text":"hello"})
        for kind,event in [("responses",{"type":"response.incomplete"}),("ollama",{"done":True,"done_reason":"length","message":{"content":"partial"}}),("openai",{"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]})]:
            with self.subTest(kind=kind),self.assertRaises(BridgeError):
                acc=StreamAccumulator(kind);acc.feed(event);acc.finish()

    def test_actual_loopback_sse_transport(self):
        observed=[]
        class Fixture(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                observed.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                events=[{"type":"response.output_text.delta","delta":"result"},{"type":"response.completed","response":final_response()}]
                payload=b"".join(("event: "+e["type"]+"\ndata: "+json.dumps(e)+"\n\n").encode() for e in events)
                self.send_response(200);self.send_header("Content-Type","text/event-stream");self.send_header("Content-Length",str(len(payload)));self.end_headers();self.wfile.write(payload)
        server=ThreadingHTTPServer(("127.0.0.1",0),Fixture);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            c=config();c["providers"]["local"]["base_url"]=f"http://127.0.0.1:{server.server_port}/v1"
            events=[];result=Runtime(c).generate(request(stream=True),events.append)
            self.assertEqual(result["text"],"result");self.assertTrue(observed[0]["stream"])
            self.assertEqual("".join(e["text"] for e in events),"result")
        finally:server.shutdown();server.server_close();thread.join(2)

if __name__=="__main__":unittest.main()
